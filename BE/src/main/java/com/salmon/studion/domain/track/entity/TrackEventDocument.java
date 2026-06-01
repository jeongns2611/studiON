package com.salmon.studion.domain.track.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class TrackEventDocument extends TrackBaseEventDocument {

    @Field("pre_track_id")
    private Integer preTrackId;

    @Field("post_track_id")
    private Integer postTrackId;
}
