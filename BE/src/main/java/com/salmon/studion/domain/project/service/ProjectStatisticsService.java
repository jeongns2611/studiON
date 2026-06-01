package com.salmon.studion.domain.project.service;

import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.clip.entity.Clip;
import com.salmon.studion.domain.clip.repository.ClipRepository;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.track.entity.Track;
import com.salmon.studion.domain.track.repository.TrackRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ProjectStatisticsService {

    private final ProjectService projectService;
    private final TrackRepository trackRepository;
    private final ClipRepository clipRepository;
    private final Clock clock;

    @Transactional
    public void refresh(Integer projectId) {
        Project project = projectService.getProjectOrThrow(projectId);
        List<Track> tracks = trackRepository.findByProject_Id(projectId);
        List<Clip> clips = clipRepository.findAllWithAudioMetadataByProjectId(projectId);

        int trackCount = tracks.size();
        double maxEndBar = calculateMaxEndBar(clips);
        int totalBarCount = calculateTotalBarCount(maxEndBar);
        int totalPlayTimeMs = calculateTotalPlayTimeMs(project, maxEndBar);
        long totalAudioSizeByte = calculateTotalAudioSizeByte(clips);

        project.refreshSnapshotStatistics(trackCount, totalBarCount, totalPlayTimeMs, totalAudioSizeByte, clock.instant());
    }

    private double calculateMaxEndBar(List<Clip> clips) {
        return clips.stream()
                .mapToDouble(clip -> clip.getStart() + clip.getDuration())
                .max()
                .orElse(0.0);
    }

    private int calculateTotalBarCount(double maxEndBar) {
        return (int) Math.ceil(maxEndBar);
    }

    private int calculateTotalPlayTimeMs(Project project, double maxEndBar) {
        if (maxEndBar <= 0) {
            return 0;
        }

        double msPerBeat = 60_000d / project.getTempo();
        double msPerBar = msPerBeat * project.getTimeSigNumerator();
        return (int) Math.ceil(maxEndBar * msPerBar);
    }

    private long calculateTotalAudioSizeByte(List<Clip> clips) {
        Map<Integer, AudioMetadata> audioById = clips.stream()
                .map(Clip::getAudioMetadata)
                .collect(Collectors.toMap(
                        AudioMetadata::getId,
                        Function.identity(),
                        (left, right) -> left
                ));
        return audioById.values().stream()
                .map(AudioMetadata::getSizeBytes)
                .filter(Objects::nonNull)
                .mapToLong(Integer::longValue)
                .sum();
    }
}
