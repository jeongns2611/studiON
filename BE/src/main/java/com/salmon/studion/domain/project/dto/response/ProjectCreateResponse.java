package com.salmon.studion.domain.project.dto.response;

import com.salmon.studion.global.common.enums.ProjectMode;
import com.salmon.studion.global.common.enums.RootNote;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class ProjectCreateResponse {

    private ProjectInfo project;
    private MasterTrackInfo masterTrack;
    private TrackInfo defaultTrack;

    public record ProjectInfo (
            Integer     projectId,
            String      name,
            RootNote    rootNote,
            ProjectMode mode,
            Double      tempo,
            Integer     timeSigNumerator,
            Integer     timeSigDenominator,
            Integer     totalBarCount,
            Integer      totalPlayTimeMs
    ) {}

    public record MasterTrackInfo(
            Integer masterTrackId,
            Boolean isSoloed,
            Boolean isMuted,
            Double volume,
            Integer pan
    ) {}

    public record TrackInfo(
            Integer trackId,
            String name,
            String type,
            Integer preTrackId,
            Integer postTrackId,
            Boolean isMuted,
            Boolean isSoloed,
            Double volume,
            Integer pan
    ) {}
}
