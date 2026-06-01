package com.salmon.studion.domain.track.dto.response;

import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Builder
public class TrackRemoveResponse {
    private Integer trackId;
    private Integer preTrackId;
    private Integer postTrackId;
}
