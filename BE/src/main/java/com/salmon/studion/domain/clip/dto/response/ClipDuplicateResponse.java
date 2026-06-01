package com.salmon.studion.domain.clip.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ClipDuplicateResponse {
    private Integer clipId;
    private Integer newClipId;
    private Integer targetTrackId;
    private Double targetStartBar;
}
