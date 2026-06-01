package com.salmon.studion.domain.clip.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class ClipPasteEventDocument extends ClipEventDocument {

    @Field("target_track_id")
    private Integer targetTrackId;

    @Field("target_start_bar")
    private Double targetStartBar;

    private Boolean undoable;
    private Boolean undone;
}
