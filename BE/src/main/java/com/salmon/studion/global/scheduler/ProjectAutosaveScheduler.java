package com.salmon.studion.global.scheduler;

import com.salmon.studion.domain.project.service.ProjectDirtyStateService;
import com.salmon.studion.domain.project.service.ProjectSaveService;
import com.salmon.studion.global.common.enums.ProjectSaveTrigger;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.support.PeriodicTrigger;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledFuture;

@Slf4j
@Component
public class ProjectAutosaveScheduler {

    private static final Duration IDLE_DELAY = Duration.ofSeconds(4);
    private static final Duration FALLBACK_INTERVAL = Duration.ofSeconds(30);

    private final TaskScheduler autosaveTaskScheduler;
    private final ProjectDirtyStateService projectDirtyStateService;
    private final ProjectSaveService projectSaveService;
    private final Clock clock;

    private final Map<Integer, ScheduledFuture<?>> pendingIdleTasks = new ConcurrentHashMap<>();

    public ProjectAutosaveScheduler(
            @Qualifier("autosaveTaskScheduler") TaskScheduler autosaveTaskScheduler,
            ProjectDirtyStateService projectDirtyStateService,
            ProjectSaveService projectSaveService,
            Clock clock
    ) {
        this.autosaveTaskScheduler = autosaveTaskScheduler;
        this.projectDirtyStateService = projectDirtyStateService;
        this.projectSaveService = projectSaveService;
        this.clock = clock;
    }

    @PostConstruct
    public void startFallbackScheduler() {
        PeriodicTrigger trigger = new PeriodicTrigger(FALLBACK_INTERVAL);
        trigger.setFixedRate(false);
        autosaveTaskScheduler.schedule(this::runFallbackSave, trigger);
        log.info("[프로젝트 autosave fallback 스케쥴러 동작 시작] - intervalSeconds={}", FALLBACK_INTERVAL.toSeconds());
    }

    public void schedule(Integer projectId) {
        projectDirtyStateService.markDirty(projectId);

        ScheduledFuture<?> previous = pendingIdleTasks.remove(projectId);
        if (previous != null) {
            previous.cancel(false);
        }

        ScheduledFuture<?> future = autosaveTaskScheduler.schedule(
                () -> {
                    pendingIdleTasks.remove(projectId);
                    projectSaveService.saveIfDirty(projectId, ProjectSaveTrigger.AUTOSAVE_IDLE);
                },
                Instant.now(clock).plus(IDLE_DELAY)
        );

        pendingIdleTasks.put(projectId, future);
    }

    private void runFallbackSave() {
        Set<Integer> dirtyProjectIds = projectDirtyStateService.getDirtyProjectIds();
        for (Integer projectId : dirtyProjectIds) {
            projectSaveService.saveIfDirty(projectId, ProjectSaveTrigger.AUTOSAVE_FALLBACK);
        }
    }
}
