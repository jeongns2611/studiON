package com.salmon.studion.domain.track.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class TrackRenameEventDocument extends TrackBaseEventDocument {

    @Field("before_track_name")
    private String beforeTrackName;

    @Field("after_track_name")
    private String afterTrackName;
}
