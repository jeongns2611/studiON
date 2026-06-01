package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.salmon.studion.global.common.enums.UserFeedbackType;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class AiUserFeedbackRequest {

    @JsonProperty("job_id")
    private Integer jobId;

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


    public static AiUserFeedbackRequest create(
        Integer jobId,
        AiUserFeedbackApiRequest request
    ) {
        return new AiUserFeedbackRequest(
                jobId,
                request.getProjectId(),
                request.getIssueId(),
                request.getActionType(),
                request.getActionPayload(),
                request.getSelectedRegionId(),
                request.getPreserveClipId(),
                request.getUserFeedbackMessage(),
                request.getUserDecision()
        );
    }
}
