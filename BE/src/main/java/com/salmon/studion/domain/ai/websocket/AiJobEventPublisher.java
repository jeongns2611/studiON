package com.salmon.studion.domain.ai.websocket;

import com.salmon.studion.domain.ai.dto.event.AiWorkflowStatusEvent;
import com.salmon.studion.domain.ai.dto.response.AiWorkflowStatusResponse;
import com.salmon.studion.global.infrastructure.websocket.WebSocketMessageSender;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Slf4j
@Component
@RequiredArgsConstructor
public class AiJobEventPublisher {

    public static final String AI_WORKFLOW_STATUS_UPDATED = "AI_WORKFLOW_STATUS_UPDATED";

    private final WebSocketMessageSender webSocketMessageSender;

    public void publishStatus(Integer projectId, AiWorkflowStatusResponse response) {
        AiWorkflowStatusEvent event = AiWorkflowStatusEvent.builder()
                .type(resolveType(response))
                .jobId(response.getJob().getId())
                .projectId(response.getJob().getProjectId())
                .status(response.getJob().getStatus())
                .phase(response.getJob().getPhase())
                .progress(response.getJob().getProgress())
                .projections(response.getProjections())
                .errorCode(response.getJob().getErrorCode())
                .errorMessage(response.getJob().getErrorMessage())
                .build();

        try {
            webSocketMessageSender.broadcast(projectId, AI_WORKFLOW_STATUS_UPDATED, event);
            log.info("AI websocket 이벤트 전송 | projectId={} jobId={} type={}",
                    projectId, event.getJobId(), event.getType());
        } catch (IOException e) {
            log.error("AI websocket 이벤트 전송 실패 | projectId={} jobId={}",
                    projectId, event.getJobId(), e);
        }
    }

    private String resolveType(AiWorkflowStatusResponse response) {
        String status = response.getJob().getStatus();
        if ("WAITING_USER".equals(status)) {
            return "JOB_WAITING_USER";
        }
        if ("COMPLETED".equals(status)) {
            return "JOB_COMPLETED";
        }
        if ("FAILED".equals(status)) {
            return "JOB_FAILED";
        }
        return "JOB_PROGRESS";
    }
}
