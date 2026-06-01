package com.salmon.studion.domain.track.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TrackVolumeResponse {
    private Integer trackId;
    private Double volume;
}
