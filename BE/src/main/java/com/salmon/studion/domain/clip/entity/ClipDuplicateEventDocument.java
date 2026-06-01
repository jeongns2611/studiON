package com.salmon.studion.domain.clip.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class ClipDuplicateEventDocument extends ClipEventDocument {

    @Field("new_clip_id")
    private Integer newClipId;

    @Field("target_track_id")
    private Integer targetTrackId;

    @Field("target_start_bar")
    private Double targetStartBar;

    private Boolean undoable;
    private Boolean undone;
}
