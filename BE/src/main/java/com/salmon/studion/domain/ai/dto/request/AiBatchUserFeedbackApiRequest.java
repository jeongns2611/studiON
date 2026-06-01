package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.salmon.studion.global.common.enums.UserFeedbackType;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;

public record AiBatchUserFeedbackApiRequest(
        @NotNull
        @JsonProperty("project_id")
        Integer projectId,

        @JsonProperty("issue_id")
        String issueId,

        @JsonProperty("action_type")
        String actionType,

        @JsonProperty("action_payload")
        JsonNode actionPayload,

        @NotEmpty
        @Valid
        @JsonProperty("selected_region_selections")
        List<AiBatchRegionSelectionRequest> selectedRegionSelections,

        @NotNull
        @JsonProperty("user_feedback_message")
        String userFeedbackMessage,

        @JsonProperty("user_decision")
        UserFeedbackType userDecision
) {
}
