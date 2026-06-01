package com.salmon.studion.domain.audio.render;

import com.salmon.studion.domain.ai.dto.request.ProjectEqBandRequest;
import com.salmon.studion.domain.ai.dto.request.ProjectTrackEqRequest;
import com.salmon.studion.domain.audio.render.dto.AudioVersionRenderSnapshot;
import com.salmon.studion.domain.clip.entity.Clip;
import com.salmon.studion.domain.clip.service.ClipService;
import com.salmon.studion.domain.limiter.dto.MasterLimiterCurrentState;
import com.salmon.studion.domain.limiter.service.MasterLimiterService;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.service.ProjectService;
import com.salmon.studion.domain.track.entity.Track;
import com.salmon.studion.domain.track.service.TrackService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class AudioVersionRenderSnapshotService {

    private static final int MIN_RENDER_DURATION_MS = 1000;

    private final ProjectService projectService;
    private final TrackService trackService;
    private final ClipService clipService;
    private final com.salmon.studion.domain.eq.service.TrackEqService trackEqService;
    private final MasterLimiterService masterLimiterService;
    private final Clock clock;

    @Transactional
    public AudioVersionRenderSnapshot createSnapshot(Integer projectId, Integer userId) {
        Project project = projectService.getProjectOrThrow(projectId);

        boolean useWorkingSet = trackService.hasTrackWorkingSet(projectId)
                || clipService.hasClipWorkingSet(projectId);

        List<Track> tracks = useWorkingSet
                ? trackService.getTracksForProjectDetail(projectId)
                : trackService.getTracksByProjectId(projectId);

        List<Clip> clips = tracks.isEmpty()
                ? List.of()
                : (useWorkingSet
                ? clipService.getClipsForProjectDetail(projectId, tracks)
                : clipService.getClipsWithAudioMetadataByTrackIds(tracks.stream().map(Track::getId).toList()));

        List<Integer> trackIds = tracks.stream().map(Track::getId).toList();
        List<ProjectTrackEqRequest> trackEqPayloads = trackEqService.getCurrentTrackEqPayloads(projectId, trackIds);
        MasterLimiterCurrentState limiterState = masterLimiterService.getCurrentState(projectId);

        Map<Integer, Boolean> renderEnabledByTrackId = resolveRenderEnabledByTrackId(tracks);
        int msPerBar = calculateMsPerBar(project);

        List<AudioVersionRenderSnapshot.RenderTrack> renderTracks = tracks.stream()
                .map(track -> AudioVersionRenderSnapshot.RenderTrack.builder()
                        .trackId(track.getId())
                        .name(track.getName())
                        .isMuted(track.getIsMuted())
                        .isSoloed(track.getIsSoloed())
                        .volume(track.getVolume())
                        .pan(track.getPan())
                        .renderEnabled(renderEnabledByTrackId.getOrDefault(track.getId(), false))
                        .build())
                .toList();

        List<AudioVersionRenderSnapshot.RenderClip> renderClips = clips.stream()
                .filter(clip -> renderEnabledByTrackId.getOrDefault(clip.getTrack().getId(), false))
                .map(clip -> toRenderClip(clip, msPerBar))
                .toList();

        int renderDurationMs = Math.max(
                renderClips.stream()
                        .map(AudioVersionRenderSnapshot.RenderClip::getTimelineEndMs)
                        .filter(value -> value != null)
                        .max(Integer::compareTo)
                        .orElse(project.getTotalPlayTimeMs()),
                MIN_RENDER_DURATION_MS
        );

        return AudioVersionRenderSnapshot.builder()
                .projectId(projectId)
                .requestedBy(userId)
                .tempo(project.getTempo().intValue())
                .numerator(project.getTimeSigNumerator())
                .denominator(project.getTimeSigDenominator())
                .renderDurationMs(renderDurationMs)
                .tracks(renderTracks)
                .clips(renderClips)
                .trackEqs(toRenderTrackEqs(trackEqPayloads))
                .masterLimiter(toRenderMasterLimiter(limiterState))
                .requestedAt(clock.instant())
                .build();
    }

    private AudioVersionRenderSnapshot.RenderClip toRenderClip(Clip clip, int msPerBar) {
        int timelineStartMs = Math.max(0, (int) Math.round((clip.getStart() - 1.0d) * msPerBar));
        int timelineEndMs = timelineStartMs + (int) Math.round(clip.getDuration() * msPerBar);

        return AudioVersionRenderSnapshot.RenderClip.builder()
                .clipId(clip.getId())
                .trackId(clip.getTrack().getId())
                .audioMetadataId(clip.getAudioMetadata().getId())
                .objectKey(clip.getAudioMetadata().getObjectKey())
                .originalName(clip.getAudioMetadata().getOriginalName())
                .timelineStartMs(timelineStartMs)
                .timelineEndMs(timelineEndMs)
                .audioStartMs(clip.getAudioStartMs())
                .audioDurationMs(clip.getAudioDurationMs())
                .build();
    }

    private List<AudioVersionRenderSnapshot.RenderTrackEq> toRenderTrackEqs(List<ProjectTrackEqRequest> trackEqPayloads) {
        return trackEqPayloads.stream()
                .map(payload -> AudioVersionRenderSnapshot.RenderTrackEq.builder()
                        .trackId(payload.getTrackId())
                        .bands(payload.getBands().stream()
                                .map(this::toRenderEqBand)
                                .toList())
                        .build())
                .toList();
    }

    private AudioVersionRenderSnapshot.RenderEqBand toRenderEqBand(ProjectEqBandRequest bandRequest) {
        return AudioVersionRenderSnapshot.RenderEqBand.builder()
                .bandOrder(bandRequest.getBandOrder())
                .eqType(bandRequest.getEqType())
                .frequencyHz(bandRequest.getFrequencyHz())
                .q(bandRequest.getQ())
                .gainDeltaDb(bandRequest.getGainDeltaDb())
                .build();
    }

    private AudioVersionRenderSnapshot.RenderMasterLimiter toRenderMasterLimiter(MasterLimiterCurrentState limiterState) {
        return AudioVersionRenderSnapshot.RenderMasterLimiter.builder()
                .isEnabled(limiterState.getIsEnabled())
                .thresholdDb(limiterState.getThresholdDb())
                .ceilingDbfs(limiterState.getCeilingDbfs())
                .attackMs(limiterState.getAttackMs())
                .releaseMs(limiterState.getReleaseMs())
                .inputGainDb(limiterState.getInputGainDb())
                .makeupGainDb(limiterState.getMakeupGainDb())
                .build();
    }

    private Map<Integer, Boolean> resolveRenderEnabledByTrackId(List<Track> tracks) {
        Set<Integer> soloTrackIds = tracks.stream()
                .filter(track -> Boolean.TRUE.equals(track.getIsSoloed()))
                .map(Track::getId)
                .collect(Collectors.toSet());

        if (!soloTrackIds.isEmpty()) {
            return tracks.stream()
                    .collect(Collectors.toMap(
                            Track::getId,
                            track -> soloTrackIds.contains(track.getId()) && !Boolean.TRUE.equals(track.getIsMuted())
                    ));
        }

        return tracks.stream()
                .collect(Collectors.toMap(
                        Track::getId,
                        track -> !Boolean.TRUE.equals(track.getIsMuted())
                ));
    }

    private int calculateMsPerBar(Project project) {
        double msPerBeat = 60_000d / project.getTempo();
        return (int) Math.round(msPerBeat * project.getTimeSigNumerator());
    }
}
