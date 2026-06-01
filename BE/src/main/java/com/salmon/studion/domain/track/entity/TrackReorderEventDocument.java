package com.salmon.studion.domain.track.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.mongodb.core.mapping.Field;

@Getter
@SuperBuilder
@NoArgsConstructor
public class TrackReorderEventDocument extends TrackBaseEventDocument {

    private TrackPosition before;

    private TrackPosition after;

    @Getter
    @SuperBuilder
    @NoArgsConstructor
    public static class TrackPosition {
        @Field("pre_track_id")
        private Integer preTrackId;

        @Field("post_track_id")
        private Integer postTrackId;
    }
}
