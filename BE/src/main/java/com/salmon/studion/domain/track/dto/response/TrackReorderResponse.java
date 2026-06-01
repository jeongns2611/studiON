package com.salmon.studion.domain.track.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TrackReorderResponse {
    private Integer trackId;
    private Integer preTrackId;
    private Integer postTrackId;
}
