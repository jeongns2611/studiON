package com.salmon.studion.domain.clip.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class ClipResizeEventDocument extends ClipEventDocument {

    private ClipSize before;
    private ClipSize after;
    private Boolean undoable;
    private Boolean undone;

    @Getter
    @SuperBuilder
    @NoArgsConstructor
    public static class ClipSize {
        @Field("start_bar")
        private Double startBar;

        @Field("length")
        private Double length;
    }
}
