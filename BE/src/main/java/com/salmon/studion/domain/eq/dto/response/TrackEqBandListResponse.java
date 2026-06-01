package com.salmon.studion.domain.eq.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class TrackEqBandListResponse {

    private List<TrackEqBandSummary> trackEqBandSummaries;

    public record TrackEqBandSummary (
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
