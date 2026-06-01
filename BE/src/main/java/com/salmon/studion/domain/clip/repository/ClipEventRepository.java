package com.salmon.studion.domain.clip.repository;

import com.salmon.studion.domain.clip.entity.ClipEventDocument;
import org.springframework.data.mongodb.repository.MongoRepository;

public interface ClipEventRepository extends MongoRepository<ClipEventDocument, String> {
}
