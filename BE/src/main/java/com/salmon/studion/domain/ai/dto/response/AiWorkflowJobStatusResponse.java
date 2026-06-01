package com.salmon.studion.domain.ai.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class AiWorkflowJobStatusResponse {

    private Integer id;

    @JsonProperty("project_id")
    private Integer projectId;

    private String status;

    private String phase;

    @JsonProperty("current_node")
    private String currentNode;

    private Integer progress;

    @JsonProperty("timeline_snapshot_id")
    private String timelineSnapshotId;

    @JsonProperty("requested_by")
    private Integer requestedBy;

    @JsonProperty("started_at")
    private String startedAt;

    @JsonProperty("completed_at")
    private String completedAt;

    @JsonProperty("error_code")
    private String errorCode;

    @JsonProperty("error_message")
    private String errorMessage;
}
