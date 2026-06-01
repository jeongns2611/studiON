package com.salmon.studion.domain.clip.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ClipResizeResponse {
    private Integer clipId;
    private ClipSize before;
    private ClipSize after;

    @Getter
    @Builder
    public static class ClipSize {
        private Double startBar;
        private Double length;
    }
}
