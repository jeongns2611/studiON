package com.salmon.studion.domain.ai.repository;

import com.salmon.studion.domain.ai.entity.AiAnalysisJob;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface AiAnalysisJobRepository extends JpaRepository<AiAnalysisJob, Integer> {
}
