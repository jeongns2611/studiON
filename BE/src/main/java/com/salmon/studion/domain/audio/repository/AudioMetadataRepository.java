package com.salmon.studion.domain.audio.repository;

import com.salmon.studion.domain.audio.entity.AudioMetadata;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface AudioMetadataRepository extends JpaRepository<AudioMetadata, Integer> {
    // TODO: 유저테스트 전용 임시 구현 (추후 수정 필요)
    @Query("""
        SELECT COALESCE(SUM(am.sizeBytes), 0)
        FROM AudioMetadata am
        WHERE am.createdBy = :userId
    """)
    Long sumSizeBytesByCreatedBy(@Param("userId") Integer userId);
}
