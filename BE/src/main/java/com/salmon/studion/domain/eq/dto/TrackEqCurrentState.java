package com.salmon.studion.domain.eq.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TrackEqCurrentState {

    private Integer projectId;
    private Integer trackId;
    private Integer trackEqId;
    private Instant updatedAt;
    private String source;
    @Builder.Default
    private List<CurrentBand> bands = List.of();

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CurrentBand {
        private Integer bandOrder;
        private String eqType;
        private Integer frequencyHz;
        private Double q;
        private Double gainDeltaDb;
        private String sourceType;
        private Integer jobId;
        private Integer suggestionActionId;
        private Integer appliedSuggestionId;
    }
}
