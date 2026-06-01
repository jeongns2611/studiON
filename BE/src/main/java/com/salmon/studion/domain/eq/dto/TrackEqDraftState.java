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
public class TrackEqDraftState {

    private Integer projectId;
    private Integer trackEqId;
    private Integer updatedBy;
    private Instant updatedAt;
    private Long version;
    private List<DraftBand> bands;

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DraftBand {
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
