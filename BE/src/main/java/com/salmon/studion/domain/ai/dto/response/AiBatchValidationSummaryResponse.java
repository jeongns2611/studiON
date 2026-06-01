package com.salmon.studion.domain.ai.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;

public record AiBatchValidationSummaryResponse(
        @JsonProperty("requestedRegions")
        Integer requestedRegions,

        @JsonProperty("successfulRegions")
        Integer successfulRegions,

        @JsonProperty("failedRegions")
        Integer failedRegions,

        @JsonProperty("criticRunRegions")
        Integer criticRunRegions,

        @JsonProperty("criticSkippedRegions")
        Integer criticSkippedRegions,

        @JsonProperty("mergedEnvelopeCount")
        Integer mergedEnvelopeCount,

        @JsonProperty("failedEnvelopeCount")
        Integer failedEnvelopeCount
) {
}
