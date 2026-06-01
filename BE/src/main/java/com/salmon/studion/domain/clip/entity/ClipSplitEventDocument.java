package com.salmon.studion.domain.clip.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class ClipSplitEventDocument extends ClipEventDocument {

    @Field("split_bar")
    private Double splitBar;

    @Field("new_clip_id")
    private Integer newClipId;

    private Boolean undoable;
    private Boolean undone;
}
