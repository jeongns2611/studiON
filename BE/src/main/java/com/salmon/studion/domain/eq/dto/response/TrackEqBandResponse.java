package com.salmon.studion.domain.eq.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@NoArgsConstructor
public class TrackEqBandResponse {

    public record TrackEqBandSummary(
            Integer trackEqBandId,
            Integer trackEqId,
            Integer bandOrder,
            String eqType,
            Integer frequencyHz,
            Double q,
            Double gainDeltaDb,
            Integer jobId,
            Integer suggestionActionId,
            Integer appliedSuggestionId,
            String sourceType
    ) {}
}
