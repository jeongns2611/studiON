package com.salmon.studion.domain.track.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TrackPanResponse {
    private Integer trackId;
    private Integer pan;
}
