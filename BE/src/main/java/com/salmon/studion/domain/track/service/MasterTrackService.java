package com.salmon.studion.domain.track.service;

import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.track.entity.MasterTrack;
import com.salmon.studion.domain.track.repository.MasterTrackRepository;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class MasterTrackService {

    private final MasterTrackRepository masterTrackRepository;

    public MasterTrack createMasterTrack(Project project) {
        return masterTrackRepository.save(MasterTrack.create(project));
    }

    public MasterTrack getMasterTrackOrThrow(Integer projectId) {
        return masterTrackRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TRACK_NOT_FOUND));
    }
}
