package com.salmon.studion.domain.ai.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;

public record AiBatchCandidatePlanResponse(
        @JsonProperty("regionId")
        Integer regionId,

        @JsonProperty("targetTrackId")
        Integer targetTrackId,

        @JsonProperty("preserveTrackId")
        Integer preserveTrackId,

        @JsonProperty("actionType")
        String actionType,

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

        @JsonProperty("validatorResult")
        String validatorResult,

        @JsonProperty("criticResult")
        String criticResult,

        @JsonProperty("criticSkipped")
        Boolean criticSkipped,

        @JsonProperty("mergeStatus")
        String mergeStatus,

        @JsonProperty("mergedIntoTrackId")
        Integer mergedIntoTrackId,

        @JsonProperty("revisionNotes")
        List<String> revisionNotes,

        @JsonProperty("params")
        JsonNode params,

        @JsonProperty("planPayload")
        JsonNode planPayload
) {
}
