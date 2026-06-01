package com.salmon.studion.domain.ai.entity;

import com.salmon.studion.domain.ai.dto.response.AiWorkflowJobResponse;
import com.salmon.studion.domain.ai.dto.response.AiWorkflowJobStatusResponse;
import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;

@Getter
@Entity
@Table(name = "ai_analysis_job")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AiAnalysisJob extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "project_id", nullable = false)
    private Integer projectId;

    @Column(name = "requested_by")
    private Integer requestedBy;

    @Column(name = "dispatch_type", length = 50)
    private String dispatchType;

    @Column(name = "status", nullable = false, length = 50)
    private String status;

    @Column(name = "phase", nullable = false, length = 100)
    private String phase;

    @Column(name = "current_node", length = 100)
    private String currentNode;

    @Column(name = "progress", nullable = false)
    private Integer progress;

    @Column(name = "queue_name", length = 100)
    private String queueName;

    @Column(name = "timeline_snapshot_id", length = 255)
    private String timelineSnapshotId;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @Column(name = "error_code", length = 100)
    private String errorCode;

    @Column(name = "error_message", length = 1000)
    private String errorMessage;

    public static AiAnalysisJob create(Integer projectId, Integer requestedBy, Instant startedAt) {
        AiAnalysisJob job = new AiAnalysisJob();
        job.projectId = projectId;
        job.requestedBy = requestedBy;
        job.status = "QUEUED";
        job.phase = "DISPATCHING";
        job.progress = 0;
        job.startedAt = startedAt;
        return job;
    }

    public void markDispatched(AiWorkflowJobResponse response) {
        this.dispatchType = response.getDispatchType();
        this.status = response.getStatus();
        this.queueName = response.getQueueName();
        this.errorCode = null;
        this.errorMessage = null;
    }

    public void syncStatus(AiWorkflowJobStatusResponse response) {
        this.projectId = response.getProjectId();
        this.requestedBy = response.getRequestedBy();
        this.status = response.getStatus();
        this.phase = response.getPhase();
        this.currentNode = response.getCurrentNode();
        this.progress = response.getProgress();
        this.timelineSnapshotId = response.getTimelineSnapshotId();
        this.startedAt = parseDateTime(response.getStartedAt(), this.startedAt);
        this.completedAt = parseDateTime(response.getCompletedAt(), this.completedAt);
        this.errorCode = response.getErrorCode();
        this.errorMessage = response.getErrorMessage();
    }

    public void markDispatchFailed(String errorCode, String errorMessage, Instant completedAt) {
        this.status = "FAILED";
        this.phase = "DISPATCH_FAILED";
        this.errorCode = errorCode;
        this.errorMessage = errorMessage;
        this.completedAt = completedAt;
    }

    private Instant parseDateTime(String value, Instant fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        try {
            return OffsetDateTime.parse(value).toInstant();
        } catch (RuntimeException ignored) {
        }
        try {
            return java.time.LocalDateTime.parse(value).toInstant(ZoneOffset.UTC);
        } catch (RuntimeException ignored) {
            return fallback;
        }
    }
}
