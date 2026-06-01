package com.salmon.studion.domain.track.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TrackState {
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
