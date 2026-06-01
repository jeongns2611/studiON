package com.salmon.studion.domain.track.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TrackRenameResponse {
    private Integer trackId;
    private String name;
}
