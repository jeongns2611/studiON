package com.salmon.studion.domain.clip.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class ClipCreateEventDocument extends ClipEventDocument {

    @Field("track_id")
    private Integer trackId;

    @Field("audio_metadata_id")
    private Integer audioMetadataId;

    @Field("start_bar")
    private Double startBar;

    @Field("duration")
    private Double duration;

    private Boolean undoable;
    private Boolean undone;
}
