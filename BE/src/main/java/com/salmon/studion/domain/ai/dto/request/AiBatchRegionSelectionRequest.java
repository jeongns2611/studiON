package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotNull;

public record AiBatchRegionSelectionRequest(
        @NotNull
        @JsonProperty("regionId")
        Integer regionId,

        @NotNull
        @JsonProperty("preserveTrackId")
        Integer preserveTrackId
) {
}
