package com.salmon.studion.domain.track.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TrackSoloResponse {
    private Integer trackId;
    private Boolean isSoloed;
}
