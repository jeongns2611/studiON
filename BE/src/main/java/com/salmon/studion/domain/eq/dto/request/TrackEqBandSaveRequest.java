package com.salmon.studion.domain.eq.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
public class TrackEqBandSaveRequest {

    @NotEmpty(message = "bands는 최소 1개 이상이어야 합니다.")
    private List<@Valid BandRequest> bands;

}
