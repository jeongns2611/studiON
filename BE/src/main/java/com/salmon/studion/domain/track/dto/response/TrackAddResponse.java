package com.salmon.studion.domain.track.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TrackAddResponse {
    private Integer trackId;
    private String name;
    private String type;
    private Integer preTrackId;
    private Integer postTrackId;
    private Boolean isMuted;
    private Boolean isSoloed;
    private Double volume;
    private Integer pan;
}
