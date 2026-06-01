package com.salmon.studion.domain.eq.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class BandRequest {

    @NotNull(message = "bandOrder는 필수입니다.")
    @Positive(message = "bandOrder는 1 이상의 값이어야 합니다.")
    private Integer bandOrder;

    @NotBlank(message = "eqType은 필수입니다.")
    private String eqType;

    @NotNull(message = "frequencyHz는 필수입니다.")
    @Positive(message = "frequencyHz는 1 이상의 값이어야 합니다.")
    private Integer frequencyHz;

    @NotNull(message = "q는 필수입니다.")
    @Positive(message = "q는 0보다 커야 합니다.")
    private Double q;

    @NotNull(message = "gainDeltaDb는 필수입니다.")
    private Double gainDeltaDb;

    @NotBlank(message = "sourceType은 필수입니다.")
    private String sourceType;


    private Integer jobId;

    private Integer suggestionActionId;

    private Integer appliedSuggestionId;
}
