package com.salmon.studion.domain.ai.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

public record AiBatchEnvelopeControlPointResponse(
        @JsonProperty("regionId")
        Integer regionId,

        @JsonProperty("startMs")
        Integer startMs,

        @JsonProperty("endMs")
        Integer endMs,

        @JsonProperty("bandLowHz")
        Integer bandLowHz,

        @JsonProperty("bandHighHz")
        Integer bandHighHz,

        @JsonProperty("gainDeltaDb")
        Double gainDeltaDb,

        @JsonProperty("params")
        JsonNode params,

        @JsonProperty("subtype")
        String subtype
) {
}
