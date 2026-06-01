package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.salmon.studion.global.common.enums.UserFeedbackType;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class AiUserFeedbackApiRequest {

    @JsonProperty("project_id")
    private Integer projectId;

    @JsonProperty("issue_id")
    private String issueId;

    @JsonProperty("action_type")
    private String actionType;

    @JsonProperty("action_payload")
    private JsonNode actionPayload;

    @JsonProperty("selected_region_id")
    private Integer selectedRegionId;

    @JsonProperty("preserve_clip_id")
    private Integer preserveClipId;

    @JsonProperty("user_feedback_message")
    private String userFeedbackMessage;

    @JsonProperty("user_decision")
    private UserFeedbackType userDecision;
}
