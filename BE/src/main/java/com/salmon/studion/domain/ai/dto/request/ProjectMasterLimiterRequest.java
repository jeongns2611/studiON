package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class ProjectMasterLimiterRequest {

    @JsonProperty("is_enabled")
    private Boolean isEnabled;

    @JsonProperty("threshold_db")
    private Double thresholdDb;

    @JsonProperty("ceiling_dbfs")
    private Double ceilingDbfs;

    @JsonProperty("attack_ms")
    private Double attackMs;

    @JsonProperty("release_ms")
    private Double releaseMs;

    @JsonProperty("input_gain_db")
    private Double inputGainDb;

    @JsonProperty("makeup_gain_db")
    private Double makeupGainDb;

    public static ProjectMasterLimiterRequest create(
            Boolean isEnabled,
            Double thresholdDb,
            Double ceilingDbfs,
            Double attackMs,
            Double releaseMs,
            Double inputGainDb,
            Double makeupGainDb
    ) {
        return new ProjectMasterLimiterRequest(
                isEnabled,
                thresholdDb,
                ceilingDbfs,
                attackMs,
                releaseMs,
                inputGainDb,
                makeupGainDb
        );
    }
}
