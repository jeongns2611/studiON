package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class ProjectTrackEqRequest {

    @JsonProperty("track_id")
    private Integer trackId;

    @JsonProperty("bands")
    private List<ProjectEqBandRequest> bands;

    public static ProjectTrackEqRequest create(Integer trackId, List<ProjectEqBandRequest> bands) {
        return new ProjectTrackEqRequest(trackId, bands);
    }
}
