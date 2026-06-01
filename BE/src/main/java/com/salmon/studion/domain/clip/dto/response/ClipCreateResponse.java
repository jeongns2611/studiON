package com.salmon.studion.domain.clip.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ClipCreateResponse {
    private Integer clipId;
    private Integer trackId;
    private Double startBar;
    private Double duration;
    private String color;
    private Integer audioMetadataId;
    private Integer audioStartMs;
    private Integer audioDurationMs;
}
