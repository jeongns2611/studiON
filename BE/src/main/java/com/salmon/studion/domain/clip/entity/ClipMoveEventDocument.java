package com.salmon.studion.domain.clip.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class ClipMoveEventDocument extends ClipEventDocument {

    private ClipPosition before;
    private ClipPosition after;
    private Boolean undoable;
    private Boolean undone;

    @Getter
    @SuperBuilder
    @NoArgsConstructor
    public static class ClipPosition {
        @Field("track_id")
        private Integer trackId;

        @Field("start_bar")
        private Double startBar;
    }
}
