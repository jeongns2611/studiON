package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.salmon.studion.global.common.enums.UserFeedbackType;

import java.util.List;

public record AiBatchUserFeedbackRequest(
        @JsonProperty("job_id")
        Integer jobId,

        @JsonProperty("project_id")
        Integer projectId,

        @JsonProperty("issue_id")
        String issueId,

        @JsonProperty("action_type")
        String actionType,

        @JsonProperty("action_payload")
        JsonNode actionPayload,

        @JsonProperty("selected_region_selections")
        List<AiBatchRegionSelectionRequest> selectedRegionSelections,

        @JsonProperty("user_feedback_message")
        String userFeedbackMessage,

        @JsonProperty("user_decision")
        UserFeedbackType userDecision
) {
    public static AiBatchUserFeedbackRequest create(
            Integer jobId,
            AiBatchUserFeedbackApiRequest request
    ) {
        return new AiBatchUserFeedbackRequest(
                jobId,
                request.projectId(),
                request.issueId(),
                request.actionType(),
                request.actionPayload(),
                request.selectedRegionSelections(),
                request.userFeedbackMessage(),
                request.userDecision()
        );
    }
}
