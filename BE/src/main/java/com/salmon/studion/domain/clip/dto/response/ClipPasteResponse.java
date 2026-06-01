package com.salmon.studion.domain.clip.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ClipPasteResponse {
    private Integer clipId;
    private Integer sourceClipId;
    private Integer targetTrackId;
    private Double targetStartBar;
}
