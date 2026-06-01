package com.salmon.studion.domain.eq.dto.response;

import com.salmon.studion.domain.eq.entity.TrackEq;
import com.salmon.studion.domain.project.entity.Project;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class TrackEqListResponse {

    private List<TrackEqSummary> trackEqs;

    public record TrackEqSummary (
            Integer trackEqId,
            Integer trackId,
            Integer projectId
    ){}
}
