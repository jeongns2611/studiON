package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class ProjectEqBandRequest {

    @JsonProperty("band_order")
    private Integer bandOrder;

    @JsonProperty("eq_type")
    private String eqType;

    @JsonProperty("frequency_hz")
    private Integer frequencyHz;

    @JsonProperty("q")
    private Double q;

    @JsonProperty("gain_delta_db")
    private Double gainDeltaDb;

    public static ProjectEqBandRequest create(
            Integer bandOrder,
            String eqType,
            Integer frequencyHz,
            Double q,
            Double gainDeltaDb
    ) {
        return new ProjectEqBandRequest(
                bandOrder,
                eqType,
                frequencyHz,
                q,
                gainDeltaDb
        );
    }
}
