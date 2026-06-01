package com.salmon.studion.domain.audio.render.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AudioVersionRenderSnapshot {

    private Integer projectId;
    private Integer requestedBy;
    private Integer tempo;
    private Integer numerator;
    private Integer denominator;
    private Integer renderDurationMs;
    private List<RenderTrack> tracks;
    private List<RenderClip> clips;
    private List<RenderTrackEq> trackEqs;
    private RenderMasterLimiter masterLimiter;
    private Instant requestedAt;

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RenderTrack {
        private Integer trackId;
        private String name;
        private Boolean isMuted;
        private Boolean isSoloed;
        private Double volume;
        private Integer pan;
        private Boolean renderEnabled;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RenderClip {
        private Integer clipId;
        private Integer trackId;
        private Integer audioMetadataId;
        private String objectKey;
        private String originalName;
        private Integer timelineStartMs;
        private Integer timelineEndMs;
        private Integer audioStartMs;
        private Integer audioDurationMs;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RenderTrackEq {
        private Integer trackId;
        private List<RenderEqBand> bands;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RenderEqBand {
        private Integer bandOrder;
        private String eqType;
        private Integer frequencyHz;
        private Double q;
        private Double gainDeltaDb;
    }

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class RenderMasterLimiter {
        private Boolean isEnabled;
        private Double thresholdDb;
        private Double ceilingDbfs;
        private Double attackMs;
        private Double releaseMs;
        private Double inputGainDb;
        private Double makeupGainDb;
    }
}
