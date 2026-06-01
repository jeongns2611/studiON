package com.salmon.studion.domain.clip.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.Instant;

@Getter
@SuperBuilder
@NoArgsConstructor
@Document(collection = "clip_edit_events")
public abstract class ClipEventDocument {

    @Id
    private String id;

    private String event;

    @Field("project_id")
    private Integer projectId;

    @Field("clip_id")
    private Integer clipId;

    @Field("user_id")
    private Integer userId;

    @Field("sequence_no")
    private Long sequenceNo;

    private Instant timestamp;
}
