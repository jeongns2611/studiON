package com.salmon.studion.domain.clip.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ClipSplitResponse {
    private Integer clipId;
    private Double splitBar;
    private Double originalDuration;
    private Integer newClipId;
    private Double newClipDuration;
}
