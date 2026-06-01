package com.salmon.studion.domain.clip.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ClipMoveResponse {
    private Integer clipId;
    private ClipPosition before;
    private ClipPosition after;

    @Getter
    @Builder
    public static class ClipPosition {
        private Integer trackId;
        private Double startBar;
    }
}
