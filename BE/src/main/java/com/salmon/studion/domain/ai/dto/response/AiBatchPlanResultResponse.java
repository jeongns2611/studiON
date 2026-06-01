package com.salmon.studion.domain.ai.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;

public record AiBatchPlanResultResponse(
        @JsonProperty("phase")
        String phase,

        @JsonProperty("request_mode")
        String requestMode,

        @JsonProperty("preview_required")
        Boolean previewRequired,

        @JsonProperty("preview_status")
        String previewStatus,

        @JsonProperty("batch_candidate_plans")
        List<AiBatchCandidatePlanResponse> batchCandidatePlans,

        @JsonProperty("batch_final_track_envelopes")
        List<AiBatchFinalTrackEnvelopeResponse> batchFinalTrackEnvelopes,

        @JsonProperty("batch_failed_regions")
        List<JsonNode> batchFailedRegions,

        @JsonProperty("batch_failed_envelopes")
        List<JsonNode> batchFailedEnvelopes,

        @JsonProperty("batch_validation_summary")
        AiBatchValidationSummaryResponse batchValidationSummary,

        @JsonProperty("suggestion_payload")
        JsonNode suggestionPayload
) {
}
