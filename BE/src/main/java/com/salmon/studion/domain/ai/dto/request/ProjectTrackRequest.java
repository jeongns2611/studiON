package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class ProjectTrackRequest {

    @JsonProperty("track_id")
    private Integer trackId;

    @JsonProperty("name")
    private String name;

    public static ProjectTrackRequest copyOf(ProjectTrackRequest source) {
        return new ProjectTrackRequest(
                source.getTrackId(),
                source.getName()
        );
    }
}
