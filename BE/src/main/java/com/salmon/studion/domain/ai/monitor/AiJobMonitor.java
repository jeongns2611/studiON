package com.salmon.studion.domain.ai.monitor;

import com.salmon.studion.domain.ai.client.FastApiClient;
import com.salmon.studion.domain.ai.dto.response.AiWorkflowStatusResponse;
import com.salmon.studion.domain.ai.repository.AiAnalysisJobRepository;
import com.salmon.studion.domain.ai.websocket.AiJobEventPublisher;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.support.PeriodicTrigger;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledFuture;

@Slf4j
@Component
public class AiJobMonitor {

    private static final Duration POLLING_INTERVAL = Duration.ofSeconds(2);

    private final FastApiClient fastApiClient;
    private final TaskScheduler taskScheduler;
    private final AiJobEventPublisher aiJobEventPublisher;
    private final AiAnalysisJobRepository aiAnalysisJobRepository;

    private final Map<Integer, ScheduledFuture<?>> pollingTasks = new ConcurrentHashMap<>();
    private final Map<Integer, String> lastStateKeys = new ConcurrentHashMap<>();

    public AiJobMonitor(
            FastApiClient fastApiClient,
            @Qualifier("aiTaskScheduler") TaskScheduler taskScheduler,
            AiJobEventPublisher aiJobEventPublisher,
            AiAnalysisJobRepository aiAnalysisJobRepository
    ) {
        this.fastApiClient = fastApiClient;
        this.taskScheduler = taskScheduler;
        this.aiJobEventPublisher = aiJobEventPublisher;
        this.aiAnalysisJobRepository = aiAnalysisJobRepository;
    }

    public void startMonitoring(Integer jobId, Integer projectId) {
        if (pollingTasks.containsKey(jobId)) {
            log.info("AI job polling 이미 실행 중 | jobId={}", jobId);
            return;
        }

        PeriodicTrigger trigger = new PeriodicTrigger(POLLING_INTERVAL);
        trigger.setFixedRate(true);
        ScheduledFuture<?> future = taskScheduler.schedule(() -> poll(jobId, projectId), trigger);
        pollingTasks.put(jobId, future);
        log.info("AI job polling 시작 | jobId={} projectId={} intervalSeconds={}",
                jobId, projectId, POLLING_INTERVAL.toSeconds());
    }

    public void stopMonitoring(Integer jobId) {
        ScheduledFuture<?> future = pollingTasks.remove(jobId);
        if (future != null) {
            future.cancel(false);
        }
        lastStateKeys.remove(jobId);
        log.info("AI job polling 종료 | jobId={}", jobId);
    }

    private void poll(Integer jobId, Integer projectId) {
        try {
            AiWorkflowStatusResponse response = fastApiClient.getWorkflowStatus(jobId);
            syncJobSnapshot(jobId, response);

            String stateKey = buildStateKey(response);
            String previousStateKey = lastStateKeys.put(jobId, stateKey);

            if (!stateKey.equals(previousStateKey)) {
                log.info("AI job 상태 변화 감지 | jobId={} status={} phase={} progress={}",
                        jobId,
                        response.getJob().getStatus(),
                        response.getJob().getPhase(),
                        response.getJob().getProgress());
                aiJobEventPublisher.publishStatus(projectId, response);
            }

            if (isTerminalStatus(response)) {
                stopMonitoring(jobId);
            }
        } catch (Exception e) {
            log.error("AI job polling 실패 | jobId={} projectId={}", jobId, projectId, e);
        }
    }

    @Transactional
    protected void syncJobSnapshot(Integer jobId, AiWorkflowStatusResponse response) {
        aiAnalysisJobRepository.findById(jobId).ifPresent(job -> job.syncStatus(response.getJob()));
    }

    private String buildStateKey(AiWorkflowStatusResponse response) {
        return String.join("|",
                nullSafe(response.getJob().getStatus()),
                nullSafe(response.getJob().getPhase()),
                String.valueOf(response.getJob().getProgress()),
                nullSafe(response.getJob().getErrorCode()),
                nullSafe(response.getJob().getErrorMessage()));
    }

    private boolean isTerminalStatus(AiWorkflowStatusResponse response) {
        String status = response.getJob().getStatus();
        return "WAITING_USER".equals(status)
                || "COMPLETED".equals(status)
                || "FAILED".equals(status)
                || "CANCELLED".equals(status)
                || "EXPIRED".equals(status);
    }

    private String nullSafe(String value) {
        return value == null ? "" : value;
    }
}
