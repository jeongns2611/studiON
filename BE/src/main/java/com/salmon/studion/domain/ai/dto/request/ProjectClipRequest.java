package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class ProjectClipRequest {

    @JsonProperty("clip_id")
    private Integer clipId;

    @JsonProperty("track_id")
    private Integer trackId;

    @JsonProperty("start_ms")
    private Integer startMs;

    @JsonProperty("end_ms")
    private Integer endMs;

    @JsonProperty("audio_metadata_id")
    private Integer audioMetadataId;

    @JsonProperty("audio_start_ms")
    private Integer audioStartMs;

    @JsonProperty("audio_duration_ms")
    private Integer audioDurationMs;

    @JsonProperty("audio_url")
    private String audioUrl;

    public static ProjectClipRequest create(ProjectClipRequest source, String audioUrl) {
        return new ProjectClipRequest(
                source.getClipId(),
                source.getTrackId(),
                source.getStartMs(),
                source.getEndMs(),
                source.getAudioMetadataId(),
                source.getAudioStartMs(),
                source.getAudioDurationMs(),
                audioUrl
        );
    }
}
