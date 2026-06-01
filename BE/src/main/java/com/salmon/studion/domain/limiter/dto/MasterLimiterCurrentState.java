package com.salmon.studion.domain.limiter.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MasterLimiterCurrentState {

    private Integer projectId;
    private Integer masterLimiterId;
    private Instant updatedAt;
    private String source;
    private Boolean isEnabled;
    private Double thresholdDb;
    private Double ceilingDbfs;
    private Double attackMs;
    private Double releaseMs;
    private Double inputGainDb;
    private Double makeupGainDb;
    private Integer jobId;
    private Integer suggestionActionId;
    private Integer appliedSuggestionId;
    private String sourceType;
}
