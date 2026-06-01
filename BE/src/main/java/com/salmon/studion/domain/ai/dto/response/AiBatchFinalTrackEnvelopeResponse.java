package com.salmon.studion.domain.ai.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

public record AiBatchFinalTrackEnvelopeResponse(
        @JsonProperty("trackId")
        Integer trackId,

        @JsonProperty("actionType")
        String actionType,

        @JsonProperty("targetStartMs")
        Integer targetStartMs,

        @JsonProperty("targetEndMs")
        Integer targetEndMs,

        @JsonProperty("bandLowHz")
        Integer bandLowHz,

        @JsonProperty("bandHighHz")
        Integer bandHighHz,

        @JsonProperty("sourceRegionIds")
        List<Integer> sourceRegionIds,

        @JsonProperty("preserveTrackIds")
        List<Integer> preserveTrackIds,

        @JsonProperty("controlPoints")
        List<AiBatchEnvelopeControlPointResponse> controlPoints
) {
}
